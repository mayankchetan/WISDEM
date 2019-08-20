"""
drivese_omdao.py

Created by Yi Guo, Taylor Parsons and Ryan King 2014.
Copyright (c) NREL. All rights reserved.

Functions nacelle_example_5MW_baseline_[34]pt() did not define blade_mass
  We've added prob['blade_mass'] = 17740.0 (copied from hubse_omdao.py)
  GNS 2019 05 13
  
GNS 2019 06 05: nacelle_example_*() now return prob
  
Classes with declarations like
  class ObjName_OM(ExplicitComponent)
are OpenMDAO wrappers for pure-python objects that define the parts of a wind turbine drivetrain.
These objects are defined in drivese_components.py (which contains NO OpenMDAO code).
"""

import numpy as np
import sys

from wisdem.drivetrainse.drivese_components import LowSpeedShaft4pt, LowSpeedShaft3pt, Gearbox, MainBearing, Bedplate, YawSystem, \
    Transformer, HighSpeedSide, Generator, NacelleSystemAdder, AboveYawMassAdder, RNASystemAdder
from wisdem.drivetrainse.hubse_omdao import HubSE, HubSE, Hub_CM_Adder_OM
from openmdao.api import Group, ExplicitComponent, IndepVarComp, Problem, view_connections

#-------------------------------------------------------------------------
# Components
#-------------------------------------------------------------------------

class LowSpeedShaft4pt_OM(ExplicitComponent):
    ''' LowSpeedShaft class
          The LowSpeedShaft class is used to represent the low speed shaft component of a wind turbine drivetrain. 
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    def initialize(self):
        self.options.declare('debug', default=False)
        
    def setup(self):
        # variables
        self.add_input('rotor_bending_moment_x', val=0.0, units='N*m', desc='The bending moment about the x axis')
        self.add_input('rotor_bending_moment_y', val=0.0, units='N*m', desc='The bending moment about the y axis')
        self.add_input('rotor_bending_moment_z', val=0.0, units='N*m', desc='The bending moment about the z axis')
        self.add_input('rotor_thrust',           val=0.0, units='N',   desc='The force along the x axis applied at hub center')
        self.add_input('rotor_force_y',          val=0.0, units='N',   desc='The force along the y axis applied at hub center')
        self.add_input('rotor_force_z',          val=0.0, units='N',   desc='The force along the z axis applied at hub center')
        self.add_input('rotor_mass',             val=0.0, units='kg',  desc='rotor mass')
        self.add_input('rotor_diameter',         val=0.0, units='m',   desc='rotor diameter')
        self.add_input('machine_rating',         val=0.0, units='kW',  desc='machine_rating machine rating of the turbine')
        self.add_input('gearbox_mass',           val=0.0, units='kg',  desc='Gearbox mass')
        self.add_input('carrier_mass',           val=0.0, units='kg',  desc='Carrier mass')
        self.add_input('overhang',               val=0.0, units='m',   desc='Overhang distance')
        self.add_input('distance_hub2mb',        val=0.0, units='m',   desc='distance between hub center and upwind main bearing')
        self.add_input('drivetrain_efficiency',  val=0.0,              desc='overall drivettrain efficiency')

        # parameters
        self.add_input('shrink_disc_mass', val=0.0,         units='kg',  desc='Mass of the shrink disc')
        self.add_input('gearbox_cm',       val=np.zeros(3), units='m',   desc='center of mass of gearbox')
        self.add_input('gearbox_length',   val=0.0,         units='m',   desc='gearbox length')
        self.add_input('flange_length',    val=0.0,         units='m',   desc='flange length')
        self.add_input('shaft_angle',      val=0.0,         units='rad', desc='Angle of the LSS inclination with respect to the horizontal')
        self.add_input('shaft_ratio',      val=0.0,                      desc='Ratio of inner diameter to outer diameter.  Leave zero for solid LSS')
      
        self.add_input('hub_flange_thickness', val=0.0, desc='Shell thickness for spherical hub')

        self.add_discrete_input('mb1Type', val='CARB', desc='main bearing #1 type- valid options are CRB/SRB/RB/CARB/TRB1/TRB2')
        self.add_discrete_input('mb2Type', val='SRB', desc='main bearing #2 type- valid options are CRB/SRB/RB/CARB/TRB1/TRB2')
        self.add_discrete_input('IEC_Class', val='B', desc='IEC turbulence class (A/B/C)')
        
        # outputs
        self.add_output('lss_design_torque',       val=0.0,         units='N*m', desc='lss design torque')
        self.add_output('lss_design_bending_load', val=0.0,         units='N',   desc='lss design bending load')
        self.add_output('lss_length',              val=0.0,         units='m',   desc='lss length')
        self.add_output('lss_diameter1',           val=0.0,         units='m',   desc='lss outer diameter at main bearing')
        self.add_output('lss_diameter2',           val=0.0,         units='m',   desc='lss outer diameter at second bearing')
        self.add_output('lss_mass',                val=0.0,         units='kg',  desc='overall component mass')
        self.add_output('lss_cm',                  val=np.zeros(3), units='m',   desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('lss_I',                   val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
        self.add_output('lss_mb1_facewidth',       val=0.0,         units='m',   desc='facewidth of upwind main bearing')
        self.add_output('lss_mb2_facewidth',       val=0.0,         units='m',   desc='facewidth of main bearing')
        self.add_output('lss_mb1_mass',            val=0.0,         units='kg',  desc='main bearing mass')
        self.add_output('lss_mb2_mass',            val=0.0,         units='kg',  desc='second bearing mass')
        self.add_output('lss_mb1_cm',              val=np.zeros(3), units='m',   desc='main bearing 1 center of mass')
        self.add_output('lss_mb2_cm',              val=np.zeros(3), units='m',   desc='main bearing 2 center of mass')

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        lss4pt = LowSpeedShaft4pt(discrete_inputs['mb1Type'], discrete_inputs['mb2Type'], discrete_inputs['IEC_Class'], debug=self.options['debug'])

        (outputs['lss_design_torque'], outputs['lss_design_bending_load'], outputs['lss_length'], outputs['lss_diameter1'], outputs['lss_diameter2'], outputs['lss_mass'], outputs['lss_cm'], outputs['lss_I'], \
         outputs['lss_mb1_facewidth'], outputs['lss_mb2_facewidth'], outputs['lss_mb1_mass'], outputs['lss_mb2_mass'], outputs['lss_mb1_cm'], outputs['lss_mb2_cm']) \
                = lss4pt.compute(inputs['rotor_diameter'], inputs['rotor_mass'], inputs['rotor_thrust'], inputs['rotor_force_y'], inputs['rotor_force_z'], \
                                    inputs['rotor_bending_moment_x'], inputs['rotor_bending_moment_y'], inputs['rotor_bending_moment_z'], \
                                    inputs['overhang'], inputs['machine_rating'], inputs['drivetrain_efficiency'], \
                                    inputs['gearbox_mass'], inputs['carrier_mass'], inputs['gearbox_cm'], inputs['gearbox_length'], \
                                    inputs['shrink_disc_mass'], inputs['flange_length'], inputs['distance_hub2mb'], inputs['shaft_angle'], inputs['shaft_ratio'], \
                                    inputs['hub_flange_thickness'])

        

#-------------------------------------------------------------------------


class LowSpeedShaft3pt_OM(ExplicitComponent):
    ''' LowSpeedShaft class
          The LowSpeedShaft class is used to represent the low speed shaft component of a wind turbine drivetrain. 
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    def initialize(self):
        self.options.declare('debug', default=False)
        
    def setup(self):
        # variables
        self.add_input('rotor_bending_moment_x', val=0.0, units='N*m', desc='The bending moment about the x axis')
        self.add_input('rotor_bending_moment_y', val=0.0, units='N*m', desc='The bending moment about the y axis')
        self.add_input('rotor_bending_moment_z', val=0.0, units='N*m', desc='The bending moment about the z axis')
        self.add_input('rotor_thrust',           val=0.0, units='N',   desc='The force along the x axis applied at hub center')
        self.add_input('rotor_force_y',          val=0.0, units='N',   desc='The force along the y axis applied at hub center')
        self.add_input('rotor_force_z',          val=0.0, units='N',   desc='The force along the z axis applied at hub center')
        self.add_input('rotor_mass',             val=0.0, units='kg',  desc='rotor mass')
        self.add_input('rotor_diameter',         val=0.0, units='m',   desc='rotor diameter')
        self.add_input('machine_rating',         val=0.0, units='kW',  desc='machine_rating machine rating of the turbine')
        self.add_input('gearbox_mass',           val=0.0, units='kg',  desc='Gearbox mass')
        self.add_input('carrier_mass',           val=0.0, units='kg',  desc='Carrier mass')
        self.add_input('overhang',               val=0.0, units='m',   desc='Overhang distance')
        self.add_input('distance_hub2mb',        val=0.0, units='m',   desc='distance between hub center and upwind main bearing')
        self.add_input('drivetrain_efficiency',  val=0.0,              desc='overall drivettrain efficiency')

        # parameters
        self.add_input('shrink_disc_mass', val=0.0,         units='kg',  desc='Mass of the shrink disc')
        self.add_input('gearbox_cm',       val=np.zeros(3), units='m',   desc='center of mass of gearbox')
        self.add_input('gearbox_length',   val=0.0,         units='m',   desc='gearbox length')
        self.add_input('flange_length',    val=0.0,         units='m',   desc='flange length')
        self.add_input('shaft_angle',      val=0.0,         units='rad', desc='Angle of the LSS inclination with respect to the horizontal')
        self.add_input('shaft_ratio',      val=0.0,                      desc='Ratio of inner diameter to outer diameter.  Leave zero for solid LSS')
        
        self.add_input('hub_flange_thickness', val=0.0, desc='Shell thickness for spherical hub')

        self.add_discrete_input('mb1Type', val='CARB', desc='main bearing #1 type- valid options are CRB/SRB/RB/CARB/TRB1/TRB2')
        self.add_discrete_input('IEC_Class', val='B', desc='IEC turbulence class (A/B/C)')
        
        # outputs
        self.add_output('lss_design_torque',       val=0.0,         units='N*m', desc='lss design torque')
        self.add_output('lss_design_bending_load', val=0.0,         units='N',   desc='lss design bending load')
        self.add_output('lss_length',              val=0.0,         units='m',   desc='lss length')
        self.add_output('lss_diameter1',           val=0.0,         units='m',   desc='lss outer diameter at main bearing')
        self.add_output('lss_diameter2',           val=0.0,         units='m',   desc='lss outer diameter at second bearing')
        self.add_output('lss_mass',                val=0.0,         units='kg',  desc='overall component mass')
        self.add_output('lss_cm',                  val=np.zeros(3),              desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('lss_I',                   val=np.zeros(3),              desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
        self.add_output('lss_mb1_facewidth',       val=0.0,         units='m',   desc='facewidth of upwind main bearing')
        self.add_output('lss_mb2_facewidth',       val=0.0,         units='m',   desc='facewidth of main bearing')
        self.add_output('lss_mb1_mass',            val=0.0,         units='kg',  desc='main bearing mass')
        self.add_output('lss_mb2_mass',            val=0.0,         units='kg',  desc='second bearing mass')
        self.add_output('lss_mb1_cm',              val=np.zeros(3), units='m',   desc='main bearing 1 center of mass')
        self.add_output('lss_mb2_cm',              val=np.zeros(3), units='m',   desc='main bearing 2 center of mass')


    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        lss3pt = LowSpeedShaft3pt(discrete_inputs['mb1Type'], discrete_inputs['IEC_Class'], debug=self.options['debug'])
        
        (outputs['lss_design_torque'], outputs['lss_design_bending_load'], outputs['lss_length'], outputs['lss_diameter1'], outputs['lss_diameter2'], outputs['lss_mass'], outputs['lss_cm'], outputs['lss_I'], \
         outputs['lss_mb1_facewidth'], outputs['lss_mb2_facewidth'], outputs['lss_mb1_mass'], outputs['lss_mb2_mass'], outputs['lss_mb1_cm'], outputs['lss_mb2_cm']) \
                = lss3pt.compute(inputs['rotor_diameter'], inputs['rotor_mass'], inputs['rotor_thrust'], inputs['rotor_force_y'], inputs['rotor_force_z'], \
                                    inputs['rotor_bending_moment_x'], inputs['rotor_bending_moment_y'], inputs['rotor_bending_moment_z'], \
                                    inputs['overhang'], inputs['machine_rating'], inputs['drivetrain_efficiency'], \
                                    inputs['gearbox_mass'], inputs['carrier_mass'], inputs['gearbox_cm'], inputs['gearbox_length'], \
                                    inputs['shrink_disc_mass'], inputs['flange_length'], inputs['distance_hub2mb'], inputs['shaft_angle'], inputs['shaft_ratio'],
                                    inputs['hub_flange_thickness'])       

        

#-------------------------------------------------------------------------

class MainBearing_OM(ExplicitComponent):
    ''' MainBearings class
          The MainBearings class is used to represent the main bearing components of a wind turbine drivetrain. It contains two subcomponents (main bearing and second bearing) which also inherit from the SubComponent class.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    def initialize(self):
        self.options.declare('bearing_position', default='main')
        
    def setup(self):
        # variables
        self.add_input('bearing_mass', val=0.0, units='kg', desc='bearing mass from LSS model')
        self.add_input('lss_diameter', val=0.0, units='m', desc='lss outer diameter at main bearing')
        self.add_input('lss_design_torque', val=0.0, units='N*m', desc='lss design torque')
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('lss_mb_cm', val=np.array([0., 0., 0.]), units='m', desc='x,y,z location from shaft model')

        # returns
        self.add_output('mb_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('mb_cm',   val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('mb_I',    val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')

        
    def compute(self, inputs, outputs):

        mb = MainBearing(self.options['bearing_position'])
        
        (outputs['mb_mass'], outputs['mb_cm'], outputs['mb_I']) \
            = mb.compute(inputs['bearing_mass'], inputs['lss_diameter'], inputs['lss_design_torque'], inputs['rotor_diameter'], inputs['lss_mb_cm'])

        

#-------------------------------------------------------------------------

class Gearbox_OM(ExplicitComponent):
    ''' Gearbox class
          The Gearbox class is used to represent the gearbox component of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    def initialize(self):
        self.options.declare('debug', default=False)
        
    def setup(self):
        # variables
        self.add_input('gear_ratio', val=0.0, desc='overall gearbox speedup ratio')
        self.add_discrete_input('planet_numbers', val=np.array([0, 0, 0,]), desc='number of planets in each stage')
        self.add_input('rotor_rpm', val=0.0, units='rpm', desc='rotor rpm at rated power')
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('rotor_torque', val=0.0, units='N*m', desc='rotor torque at rated power')
        self.add_input('gearbox_input_xcm', val=0.00, units='m', desc='gearbox position along x-axis')

        self.add_discrete_input('gear_configuration', val='eep', desc='string that represents the configuration of the gearbox (stage number and types)')
        self.add_discrete_input('shaft_factor', val='normal', desc='normal or short shaft length')
        
        # outputs
        self.add_output('stage_masses', val=np.zeros(3), units='kg', desc='individual gearbox stage gearbox_masses')
        self.add_output('gearbox_mass', val=0.0, units='kg', desc='overall component gearbox_mass')
        self.add_output('gearbox_cm', val=np.zeros(3), units='m', desc='center of gearbox_mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('gearbox_I', val=np.zeros(3), units='kg*m**2', desc=' moments of gearbox_Inertia for the component [gearbox_Ixx, gearbox_Iyy, gearbox_Izz] around its center of gearbox_mass')
        self.add_output('gearbox_length', val=0.0, units='m', desc='gearbox length')
        self.add_output('gearbox_height', val=0.0, units='m', desc='gearbox height')
        self.add_output('gearbox_diameter', val=0.0, units='m', desc='gearbox diameter')


    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        mygearbox = Gearbox(discrete_inputs['gear_configuration'], discrete_inputs['shaft_factor'], debug=self.options['debug'])
        
        (outputs['stage_masses'], outputs['gearbox_mass'], outputs['gearbox_cm'], outputs['gearbox_I'], outputs['gearbox_length'], outputs['gearbox_height'], outputs['gearbox_diameter']) \
            = mygearbox.compute(inputs['gear_ratio'], discrete_inputs['planet_numbers'], inputs['rotor_rpm'], inputs['rotor_diameter'], inputs['rotor_torque'], inputs['gearbox_input_xcm'])

        

#-------------------------------------------------------------------

class HighSpeedSide_OM(ExplicitComponent):
    '''
    HighSpeedShaft class
          The HighSpeedShaft class is used to represent the high speed shaft and mechanical brake components of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    def setup(self):

        # variables
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('rotor_torque', val=0.0, units='N*m', desc='rotor torque at rated power')
        self.add_input('gear_ratio', val=0.0, desc='overall gearbox ratio')
        self.add_input('lss_diameter', val=0.0, units='m', desc='low speed shaft outer diameter')
        self.add_input('gearbox_length', val=0.0, units='m', desc='gearbox length')
        self.add_input('gearbox_height', val=0.0, units='m', desc='gearbox height')
        self.add_input('gearbox_cm', val=np.zeros(3), units='m', desc='gearbox cm [x,y,z]')
        self.add_input('hss_input_length', val=0.0, units='m', desc='high speed shaft length determined by user. Default 0.5m')

        # returns
        self.add_output('hss_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('hss_cm', val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('hss_I', val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
        self.add_output('hss_length', val=0.0, units='m', desc='length of high speed shaft')

        self.hss = HighSpeedSide()

    def compute(self, inputs, outputs):

        (outputs['hss_mass'], outputs['hss_cm'], outputs['hss_I'], outputs['hss_length']) \
            = self.hss.compute(inputs['rotor_diameter'], inputs['rotor_torque'], inputs['gear_ratio'], inputs['lss_diameter'], inputs['gearbox_length'], inputs['gearbox_height'], inputs['gearbox_cm'], inputs['hss_input_length'])

        

#----------------------------------------------------------------------------------------------

class Generator_OM(ExplicitComponent):
    '''Generator class
          The Generator class is used to represent the generator of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

        
    def setup(self):
        # variables
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('machine_rating', val=0.0, units='kW', desc='machine rating of generator')
        self.add_input('gear_ratio', val=0.0, desc='overall gearbox ratio')
        self.add_input('hss_length', val=0.0, units='m', desc='length of high speed shaft and brake')
        self.add_input('hss_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='cm of high speed shaft and brake')
        self.add_input('rotor_rpm', val=0.0, units='rpm', desc='Speed of rotor at rated power')
        
        self.add_discrete_input('drivetrain_design', val='geared', desc='geared or single_stage or multi_drive or pm_direct_drive')

        #returns
        self.add_output('generator_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('generator_cm', val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('generator_I', val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        mygen = Generator(discrete_inputs['drivetrain_design'])
        
        (outputs['generator_mass'], outputs['generator_cm'], outputs['generator_I']) \
            = mygen.compute(inputs['rotor_diameter'], inputs['machine_rating'], inputs['gear_ratio'], inputs['hss_length'], inputs['hss_cm'], inputs['rotor_rpm'])

        

#--------------------------------------------

class RNASystemAdder_OM(ExplicitComponent):
    ''' RNASystem class
          This analysis is only to be used in placing the transformer of the drivetrain.
          The Rotor-Nacelle-Group class is used to represent the RNA of the turbine without the transformer and bedplate (to resolve circular dependency issues).
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component. 
    '''

    def setup(self):

        # inputs
        self.add_input('lss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb1_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb2_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('gearbox_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('hss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('generator_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('lss_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('mb1_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('mb2_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('gearbox_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('hss_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('generator_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('overhang', val=0.0, units='m', desc='nacelle overhang')
        self.add_input('rotor_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('machine_rating', val=0.0, units='kW', desc='machine rating')

        # returns
        self.add_output('RNA_mass', val=0.0, units='kg', desc='mass of total RNA')
        self.add_output('RNA_cm', val=0.0, units='m', desc='RNA CM along x-axis')
        
        
    def compute(self, inputs, outputs):

        rnaadder = RNASystemAdder()
        (outputs['RNA_mass'], outputs['RNA_cm']) \
                    = rnaadder.compute(inputs['lss_mass'], inputs['mb1_mass'], inputs['mb2_mass'], inputs['gearbox_mass'], inputs['hss_mass'], inputs['generator_mass'], \
                      inputs['lss_cm'], inputs['mb1_cm'], inputs['mb2_cm'], inputs['gearbox_cm'], inputs['hss_cm'], inputs['generator_cm'], inputs['overhang'], inputs['rotor_mass'], inputs['machine_rating'])

        
        
#-------------------------------------------------------------------------------

class Transformer_OM(ExplicitComponent):
    ''' Transformer class
            The transformer class is used to represent the transformer of a wind turbine drivetrain.
            It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
            It contains an update method to determine the mass, mass properties, and dimensions of the component if it is in fact uptower'''

        
    def setup(self):

        # inputs
        self.add_input('machine_rating', val=0.0, units='kW', desc='machine rating of the turbine')
        self.add_input('tower_top_diameter', val=0.0, units='m', desc='tower top diameter for comparision of nacelle CM')
        self.add_input('rotor_mass', val=0.0, units='kg', desc='rotor mass')
        self.add_input('generator_cm', val=np.zeros(3), units='m', desc='center of mass of the generator in [x,y,z]')
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter of turbine')
        self.add_input('RNA_mass', val=0.0, units='kg', desc='mass of total RNA')
        self.add_input('RNA_cm', val=0.0, units='m', desc='RNA CM along x-axis')

        self.add_discrete_input('uptower_transformer', val=True)
        
        # outputs
        self.add_output('transformer_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('transformer_cm', val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('transformer_I', val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    


    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        transformer = Transformer(discrete_inputs['uptower_transformer'])
        (outputs['transformer_mass'], outputs['transformer_cm'], outputs['transformer_I']) \
            = transformer.compute(inputs['machine_rating'], inputs['tower_top_diameter'], inputs['rotor_mass'], inputs['generator_cm'], inputs['rotor_diameter'], inputs['RNA_mass'], inputs['RNA_cm'])

        

#-------------------------------------------------------------------------

class Bedplate_OM(ExplicitComponent):
    ''' Bedplate class
          The Bedplate class is used to represent the bedplate of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    def initialize(self):
        self.options.declare('debug', default=False)

    def setup(self):
        # variables
        self.add_input('gearbox_length', val=0.0, units='m', desc='gearbox length')
        self.add_input('gearbox_location', val=0.0, units='m', desc='gearbox CM location')
        self.add_input('gearbox_mass', val=0.0, units='kg', desc='gearbox mass')
        self.add_input('hss_location', val=0.0, units='m', desc='HSS CM location')
        self.add_input('hss_mass', val=0.0, units='kg', desc='HSS mass')
        self.add_input('generator_location', val=0.0, units='m', desc='generator CM location')
        self.add_input('generator_mass', val=0.0, units='kg', desc='generator mass')
        self.add_input('lss_location', val=0.0, units='m', desc='LSS CM location')
        self.add_input('lss_mass', val=0.0, units='kg', desc='LSS mass')
        self.add_input('lss_length', val=0.0, units='m', desc='LSS length')
        self.add_input('lss_mb1_facewidth', val=0.0, units='m', desc='Upwind main bearing facewidth')
        self.add_input('mb1_cm', val=np.zeros(3), units='m', desc='Upwind main bearing CM location')
        self.add_input('mb1_mass', val=0.0, units='kg', desc='Upwind main bearing mass')
        self.add_input('mb2_cm', val=np.zeros(3), units='m', desc='Downwind main bearing CM location')
        self.add_input('mb2_mass', val=0.0, units='kg', desc='Downwind main bearing mass')
        self.add_input('transformer_mass', val=0.0, units='kg', desc='Transformer mass')
        self.add_input('transformer_cm', val=np.zeros(3), units='m', desc='transformer CM location')
        self.add_input('tower_top_diameter', val=0.0, units='m', desc='diameter of the top tower section at the yaw gear')
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('machine_rating', val=0.0, units='kW', desc='machine_rating machine rating of the turbine')
        self.add_input('rotor_mass', val=0.0, units='kg', desc='rotor mass')
        self.add_input('rotor_bending_moment_y', val=0.0, units='N*m', desc='The bending moment about the y axis')
        self.add_input('rotor_force_z', val=0.0, units='N', desc='The force along the z axis applied at hub center')
        self.add_input('flange_length', val=0.0, units='m', desc='flange length')
        self.add_input('distance_hub2mb', val=0.0, units='m', desc='length between rotor center and upwind main bearing')

        self.add_discrete_input('uptower_transformer', val=True)
        
        # outputs
        self.add_output('bedplate_mass', val=0.0, units='kg', desc='overall component bedplate_mass')
        self.add_output('bedplate_cm', val=np.zeros(3), units='m', desc='center of bedplate_mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('bedplate_I', val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of bedplate_mass')
        self.add_output('bedplate_length', val=0.0, units='m', desc='length of bedplate')
        self.add_output('bedplate_height', val=0.0, units='m',  desc='max height of bedplate')
        self.add_output('bedplate_width', val=0.0, units='m', desc='width of bedplate')
        

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        bpl = Bedplate(discrete_inputs['uptower_transformer'], debug=self.options['debug'])
        
        (outputs['bedplate_mass'], outputs['bedplate_cm'], outputs['bedplate_I'], outputs['bedplate_length'], outputs['bedplate_height'], outputs['bedplate_width']) \
            = bpl.compute(inputs['gearbox_length'], inputs['gearbox_location'], inputs['gearbox_mass'], inputs['hss_location'], inputs['hss_mass'], inputs['generator_location'], inputs['generator_mass'], \
                      inputs['lss_location'], inputs['lss_mass'], inputs['lss_length'], inputs['mb1_cm'], inputs['lss_mb1_facewidth'], inputs['mb1_mass'], inputs['mb2_cm'], inputs['mb2_mass'], \
                      inputs['transformer_mass'], inputs['transformer_cm'], \
                      inputs['tower_top_diameter'], inputs['rotor_diameter'], inputs['machine_rating'], inputs['rotor_mass'], inputs['rotor_bending_moment_y'], inputs['rotor_force_z'], \
                      inputs['flange_length'], inputs['distance_hub2mb'])

        

#-------------------------------------------------------------------------------

class AboveYawMassAdder_OM(ExplicitComponent):
    ''' AboveYawMassAdder_OM class
          The AboveYawMassAdder_OM class is used to represent the masses of all parts of a wind turbine drivetrain that
          are above the yaw system.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    def initialize(self):
        self.options.declare('debug', default=False)

    def setup(self):
        # variables
        self.add_input('machine_rating', val=0.0, units='kW', desc='machine rating')
        self.add_input('lss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb1_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb2_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('gearbox_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('hss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('generator_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('bedplate_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('bedplate_length', val=0.0, units='m', desc='component length')
        self.add_input('bedplate_width', val=0.0, units='m', desc='component width')
        self.add_input('transformer_mass', val=0.0, units='kg', desc='component mass')

        self.add_discrete_input('crane', val=True, desc='onboard crane present')
        
        # returns
        self.add_output('electrical_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('vs_electronics_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('hvac_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('controls_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('platforms_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('crane_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('mainframe_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('cover_mass', val=0.0, units='kg', desc='component mass')
        self.add_output('above_yaw_mass', val=0.0, units='kg', desc='total mass above yaw system')
        self.add_output('nacelle_length', val=0.0, units='m', desc='component length')
        self.add_output('nacelle_width', val=0.0, units='m', desc='component width')
        self.add_output('nacelle_height', val=0.0, units='m', desc='component height')
        

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        aboveyawmass = AboveYawMassAdder(discrete_inputs['crane'])

        (outputs['electrical_mass'], outputs['vs_electronics_mass'], outputs['hvac_mass'], outputs['controls_mass'], 
         outputs['platforms_mass'], outputs['crane_mass'], outputs['mainframe_mass'], outputs['cover_mass'], 
         outputs['above_yaw_mass'], outputs['nacelle_length'], outputs['nacelle_width'], outputs['nacelle_height']) \
            = aboveyawmass.compute(inputs['machine_rating'], inputs['lss_mass'], inputs['mb1_mass'], inputs['mb2_mass'], 
                    inputs['gearbox_mass'], inputs['hss_mass'], inputs['generator_mass'], inputs['bedplate_mass'], 
                    inputs['bedplate_length'], inputs['bedplate_width'], inputs['transformer_mass'])
        
        if self.options['debug']:
            print('AYMA IN: {:.1f} kW BPl {:.1f} m BPw {:.1f} m'.format(
                  inputs['machine_rating'],inputs['bedplate_length'], inputs['bedplate_width']))
            print('AYMA IN  masses (kg): LSS {:.1f} MB1 {:.1f} MB2 {:.1f} GBOX {:.1f} HSS {:.1f} GEN {:.1f} BP {:.1f} TFRM {:.1f}'.format(
                  inputs['lss_mass'], inputs['mb1_mass'], inputs['mb2_mass'], inputs['gearbox_mass'],
                  inputs['hss_mass'], inputs['generator_mass'], inputs['bedplate_mass'], inputs['transformer_mass']))
            print('AYMA OUT masses (kg) : E {:.1f} VSE {:.1f} HVAC {:.1f} CNTL {:.1f} PTFM {:.1f} CRN {:.1f} MNFRM {:.1f} CVR {:.1f} AYM {:.1f}'.format( 
                  outputs['electrical_mass'], outputs['vs_electronics_mass'], outputs['hvac_mass'], outputs['controls_mass'],
                  outputs['platforms_mass'], outputs['crane_mass'], outputs['mainframe_mass'], outputs['cover_mass'],
                  outputs['above_yaw_mass']))
            print('AYMA OUT nacelle (m): L {:.2f} W {:.2f} H {:.2f}'.format( 
                 outputs['nacelle_length'], outputs['nacelle_width'], outputs['nacelle_height']))

        

#---------------------------------------------------------------------------------------------------------------

class YawSystem_OM(ExplicitComponent):
    ''' YawSystem class
          The YawSystem class is used to represent the yaw system of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    def setup(self):
        # variables
        self.add_input('rotor_diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_input('rotor_thrust', val=0.0, units='N', desc='maximum rotor thrust')
        self.add_input('tower_top_diameter', val=0.0, units='m', desc='tower top diameter')
        self.add_input('above_yaw_mass', val=0.0, units='kg', desc='above yaw mass')
        self.add_input('bedplate_height', val=0.0, units='m', desc='bedplate height')

        self.add_discrete_input('yaw_motors_number', val=0, desc='default value - will be internally calculated')
        
        # outputs
        self.add_output('yaw_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('yaw_cm', val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('yaw_I', val=np.zeros(3), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        myyaw = YawSystem(discrete_inputs['yaw_motors_number'])

        (outputs['yaw_mass'], outputs['yaw_cm'], outputs['yaw_I']) \
            = myyaw.compute(inputs['rotor_diameter'], inputs['rotor_thrust'], inputs['tower_top_diameter'], inputs['above_yaw_mass'], inputs['bedplate_height'])

        

#--------------------------------------------
class NacelleSystemAdder_OM(ExplicitComponent): #added to drive to include transformer
    ''' NacelleSystem class
          The Nacelle class is used to represent the overall nacelle of a wind turbine.
          It contains the general properties for a wind turbine component as well as additional design load and dimensional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    def setup(self):

        # variables
        self.add_input('above_yaw_mass', val=0.0, units='kg', desc='mass above yaw system')
        self.add_input('yaw_mass', val=0.0, units='kg', desc='mass of yaw system')
        self.add_input('lss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb1_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mb2_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('gearbox_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('hss_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('generator_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('bedplate_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('mainframe_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('lss_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('mb1_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('mb2_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('gearbox_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('hss_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('generator_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('bedplate_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('lss_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('mb1_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('mb2_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('gearbox_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('hss_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('generator_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('bedplate_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')
        self.add_input('transformer_mass', val=0.0, units='kg', desc='component mass')
        self.add_input('transformer_cm', val=np.array([0.0,0.0,0.0]), units='m', desc='component CM')
        self.add_input('transformer_I', val=np.array([0.0,0.0,0.0]), units='kg*m**2', desc='component I')

        # returns
        self.add_output('nacelle_mass', val=0.0, units='kg', desc='overall component mass')
        self.add_output('nacelle_cm', val=np.zeros(3), units='m', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
        self.add_output('nacelle_I', val=np.zeros(6), units='kg*m**2', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')

        
    def compute(self, inputs, outputs):
        nacelleadder = NacelleSystemAdder()

        (outputs['nacelle_mass'], outputs['nacelle_cm'], outputs['nacelle_I']) \
                    = nacelleadder.compute(inputs['above_yaw_mass'], inputs['yaw_mass'], inputs['lss_mass'], inputs['mb1_mass'], inputs['mb2_mass'], inputs['gearbox_mass'], \
                      inputs['hss_mass'], inputs['generator_mass'], inputs['bedplate_mass'], inputs['mainframe_mass'], \
                      inputs['lss_cm'], inputs['mb1_cm'], inputs['mb2_cm'], inputs['gearbox_cm'], inputs['hss_cm'], inputs['generator_cm'], inputs['bedplate_cm'], \
                      inputs['lss_I'], inputs['mb1_I'], inputs['mb2_I'], inputs['gearbox_I'], inputs['hss_I'], inputs['generator_I'], inputs['bedplate_I'], \
                      inputs['transformer_mass'], inputs['transformer_cm'], inputs['transformer_I'])

        

#-------------------------------------------------------------------------
# Groups
#   (were Assemblies in OpenMDAO 0.x)
#------------------------------------------------------------------

class DriveSE(Group):
    ''' Class Drive4pt defines an OpenMDAO group that represents a wind turbine drivetrain with a 4-point suspension
      (two main bearings). This Group can serve as the root of an OpenMDAO Problem.
    It contains the following components:
        HubMassOnlySE()
        LowSpeedShaft3pt_OM()
        MainBearing_OM('main')
        MainBearing_OM('second')
        Hub_CM_Adder_OM()
        Gearbox_OM()
        HighSpeedSide_OM()
        Generator_OM()
        Bedplate_OM()
        Transformer_OM()
        RNASystemAdder_OM()
        AboveYawMassAdder_OM()
        YawSystem_OM()
        NacelleSystemAdder_OM()
    '''

    def initialize(self):
        self.options.declare('number_of_main_bearings')
        self.options.declare('topLevelFlag', default=True)
        self.options.declare('debug', default=False)
        
    def setup(self):
        debug=self.options['debug']
        if not self.options['number_of_main_bearings'] in [1,2]:
            raise ValueError('Number of main bearings must be one or two')
        elif self.options['number_of_main_bearings'] == 2:
            drive4pt = True
        else:
            drive4pt = False

        # Independent variables that are unique to DriveSE
        driveIndeps = IndepVarComp()
        driveIndeps.add_output('gear_ratio', 0.0)
        driveIndeps.add_output('shaft_angle', 0.0, units='rad')
        driveIndeps.add_output('shaft_ratio', 0.0)
        driveIndeps.add_output('shrink_disc_mass', 0.0, units='kg')
        driveIndeps.add_output('carrier_mass', 0.0, units='kg')
        driveIndeps.add_output('flange_length', 0.0, units='m')
        driveIndeps.add_output('overhang', 0.0, units='m')
        driveIndeps.add_output('distance_hub2mb', 0.0, units='m')
        driveIndeps.add_output('gearbox_input_xcm', 0.0, units='m')
        driveIndeps.add_output('hss_input_length', 0.0, units='m')
        driveIndeps.add_discrete_output('planet_numbers', np.array([0, 0, 0]))
        driveIndeps.add_discrete_output('drivetrain_design', 'geared')
        driveIndeps.add_discrete_output('gear_configuration', 'eep')
        if drive4pt:
            driveIndeps.add_discrete_output('mb1Type', 'CARB')
            driveIndeps.add_discrete_output('mb2Type', 'SRB')
        else:
            driveIndeps.add_discrete_output('mb1Type', 'SRB')
        driveIndeps.add_discrete_output('IEC_Class', 'B')
        driveIndeps.add_discrete_output('shaft_factor', 'normal')
        driveIndeps.add_discrete_output('uptower_transformer', True)
        driveIndeps.add_discrete_output('crane', True)
        driveIndeps.add_discrete_output('yaw_motors_number', 0)
        self.add_subsystem('driveIndeps', driveIndeps, promotes=['*'])

        # Independent variables that may be duplicated at higher levels of aggregation
        if self.options['topLevelFlag']:
            sharedIndeps = IndepVarComp()
            sharedIndeps.add_discrete_output('number_of_blades', 0)
            sharedIndeps.add_output('tower_top_diameter',     0.0, units='m')
            sharedIndeps.add_output('rotor_diameter',         0.0, units='m')
            sharedIndeps.add_output('rotor_rpm',              0.0, units='rpm')
            sharedIndeps.add_output('rotor_torque',           0.0, units='N*m')
            sharedIndeps.add_output('rotor_thrust',           0.0, units='N')
            sharedIndeps.add_output('rotor_bending_moment_x', 0.0, units='N*m')
            sharedIndeps.add_output('rotor_bending_moment_y', 0.0, units='N*m')
            sharedIndeps.add_output('rotor_bending_moment_z', 0.0, units='N*m')
            sharedIndeps.add_output('rotor_force_y',          0.0, units='N')
            sharedIndeps.add_output('rotor_force_z',          0.0, units='N')
            sharedIndeps.add_output('blade_mass',             0.0, units='kg')
            sharedIndeps.add_output('blade_root_diameter',    0.0, units='m')
            sharedIndeps.add_output('blade_length',           0.0, units='m')
            sharedIndeps.add_output('drivetrain_efficiency',  0.0)
            sharedIndeps.add_output('machine_rating',         0.0, units='kW')
            self.add_subsystem('sharedIndeps', sharedIndeps, promotes=['*'])

        # select components
        self.add_subsystem('hub', HubSE(mass_only=True, topLevelFlag=False, debug=debug), promotes=['*'])
        self.add_subsystem('lowSpeedShaft', LowSpeedShaft4pt_OM(), promotes=['*'])
        self.add_subsystem('mainBearing', MainBearing_OM(bearing_position='main'), promotes=['lss_design_torque','rotor_diameter']) #explicit connections for bearings
        if drive4pt:
            self.add_subsystem('secondBearing', MainBearing_OM(bearing_position='second'), promotes=['lss_design_torque','rotor_diameter']) #explicit connections for bearings
        self.add_subsystem('hubCM', Hub_CM_Adder_OM(), promotes=['*'])
        self.add_subsystem('gearbox', Gearbox_OM(), promotes=['*'])
        self.add_subsystem('highSpeedSide', HighSpeedSide_OM(), promotes=['*'])
        self.add_subsystem('generator', Generator_OM(), promotes=['*'])
        self.add_subsystem('bedplate', Bedplate_OM(), promotes=['*'])
        self.add_subsystem('transformer', Transformer_OM(), promotes=['*'])
        self.add_subsystem('rna', RNASystemAdder_OM(), promotes=['*'])
        self.add_subsystem('above_yaw_massAdder', AboveYawMassAdder_OM(), promotes=['*'])
        self.add_subsystem('yawSystem', YawSystem_OM(), promotes=['*'])
        self.add_subsystem('nacelleSystem', NacelleSystemAdder_OM(), promotes=['*'])

        # Connect components where explicit connections needed (for main bearings)
        self.connect('lss_mb1_mass',        ['mainBearing.bearing_mass'])
        self.connect('lss_diameter1',       ['mainBearing.lss_diameter', 'lss_diameter'])
        self.connect('lss_mb1_cm',          ['mainBearing.lss_mb_cm'])
        self.connect('mainBearing.mb_mass', ['mb1_mass'])
        self.connect('mainBearing.mb_cm',   ['mb1_cm', 'MB1_location'])
        self.connect('mainBearing.mb_I',    ['mb1_I'])

        if drive4pt:
            self.connect('lss_mb2_mass',          ['secondBearing.bearing_mass'])
            self.connect('lss_diameter2',         ['secondBearing.lss_diameter'])
            self.connect('lss_mb2_cm',            ['secondBearing.lss_mb_cm'])
            self.connect('secondBearing.mb_mass', ['mb2_mass'])
            self.connect('secondBearing.mb_cm',   ['mb2_cm'])
            self.connect('secondBearing.mb_I',    ['mb2_I'])

        self.connect('lss_cm',       'lss_location',       src_indices=[0])
        self.connect('hss_cm',       'hss_location',       src_indices=[0])
        self.connect('gearbox_cm',   'gearbox_location',   src_indices=[0])
        self.connect('generator_cm', 'generator_location', src_indices=[0])

#------------------------------------------------------------------
# examples

def nacelle_example_5MW_baseline_3pt(debug=False):

    # NREL 5 MW Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine

    runid = 'N5_3pt'
    modid = ''
    
    prob=Problem()
    prob.model=DriveSE(debug=debug, number_of_main_bearings=1, topLevelFlag=True)
    prob.setup()
    #view_connections(prob.model, show_browser=True)

    prob['drivetrain_design']='geared'
    prob['gear_configuration']='eep'  # epicyclic-epicyclic-parallel
    prob['mb1Type']='SRB'
    prob['IEC_Class']='B'
    prob['shaft_factor']='normal'
    prob['uptower_transformer']=True
    prob['crane']=True  # onboard crane present
    prob['yaw_motors_number'] = 0 # default value - will be internally calculated
    prob['number_of_blades'] = 3
    
    # Rotor and load inputs
    prob['rotor_diameter'] = 126.0  # m
    prob['rotor_rpm'] = 12.1  # rpm m/s
    prob['machine_rating'] = 5000.0
    prob['drivetrain_efficiency'] = 0.95
    prob['rotor_torque'] = 1.5 * (prob['machine_rating'] * 1000 / prob['drivetrain_efficiency']) \
                              / (prob['rotor_rpm'] * (np.pi / 30))
    #prob['rotor_thrust'] = 599610.0  # N
    prob['rotor_mass'] = 0.0  # accounted for in F_z # kg
    prob['rotor_bending_moment_x'] =    330770.0  # Nm
    prob['rotor_bending_moment_y'] = -16665000.0  # Nm
    prob['rotor_bending_moment_z'] =   2896300.0  # Nm
    prob['rotor_thrust'] =   599610.0  # N
    prob['rotor_force_y'] =  186780.0  # N
    prob['rotor_force_z'] = -842710.0  # N

    # Drivetrain inputs
    prob['machine_rating'] = 5000.0  # kW
    prob['gear_ratio'] = 96.76  # 97:1 as listed in the 5 MW reference document
    prob['shaft_angle'] = 5.0*np.pi / 180.0  # rad
    prob['shaft_ratio'] = 0.10 # 0.10 may be a bit small!
    prob['planet_numbers'] = [3, 3, 1]
    prob['shrink_disc_mass'] = 333.3 * prob['machine_rating'] / 1000.0  # estimated
    prob['carrier_mass'] = 8000.0  # estimated
    #prob['flange_length'] = 0.5
    prob['overhang'] = 5.0
    prob['distance_hub2mb'] = 1.912  # length from hub center to main bearing, leave zero if unknown
    prob['gearbox_input_xcm'] = 0.1
    prob['hss_input_length'] = 1.5

    # try this:
    prob['blade_mass'] = 17740.0
    prob['blade_root_diameter'] = 2.5
    prob['blade_length'] = 60.0
    
    # Tower inputs
    prob['tower_top_diameter'] = 3.78  # m

    # test cases
    #prob['rotor_mass'] = 1000; modid = '_r1k'
    
    prob.run_driver()
    prob.model.list_inputs(units=True)#values = False, hierarchical=False)
    prob.model.list_outputs(units=True)#values = False, hierarchical=False)    

    return prob

#-------------------------------------------------------------------------

def nacelle_example_5MW_baseline_4pt(debug=False):

    # NREL 5 MW Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine
    prob=Problem()
    prob.model=DriveSE(debug=debug, number_of_main_bearings=2, topLevelFlag=True)
    prob.setup()

    prob['drivetrain_design']='geared'
    prob['gear_configuration']='eep'  # epicyclic-epicyclic-parallel
    prob['mb1Type']='CARB'
    prob['mb2Type']='SRB'
    prob['IEC_Class']='B'
    prob['shaft_factor']='normal'
    prob['uptower_transformer']=True
    prob['crane']=True  # onboard crane present
    prob['yaw_motors_number'] = 0 # default value - will be internally calculated
    prob['number_of_blades'] = 3
    
    # Rotor and load inputs
    prob['rotor_diameter'] = 126.0  # m
    prob['rotor_rpm'] = 12.1  # rpm m/s
    prob['machine_rating'] = 5000.0
    prob['drivetrain_efficiency'] = 0.95
    prob['rotor_torque'] = 1.5 * (prob['machine_rating'] * 1000 / \
                             prob['drivetrain_efficiency']) / (prob['rotor_rpm'] * (np.pi / 30))
    prob['rotor_mass'] = 0.0  # accounted for in F_z # kg
    prob['rotor_bending_moment_x'] =    330770.0  # Nm
    prob['rotor_bending_moment_y'] = -16665000.0  # Nm
    prob['rotor_bending_moment_z'] =   2896300.0  # Nm
    prob['rotor_thrust'] =   599610.0  # N
    prob['rotor_force_y'] =  186780.0  # N
    prob['rotor_force_z'] = -842710.0  # N

    # Drivetrain inputs
    prob['machine_rating'] = 5000.0  # kW
    prob['gear_ratio'] = 96.76  # 97:1 as listed in the 5 MW reference document
    prob['shaft_angle'] = 5.0*np.pi / 180.0  # rad
    prob['shaft_ratio'] = 0.10
    prob['planet_numbers'] = [3, 3, 1]
    prob['shrink_disc_mass'] = 333.3 * prob['machine_rating'] / 1000.0  # estimated
    prob['carrier_mass'] = 8000.0  # estimated
    prob['flange_length'] = 0.5
    prob['overhang'] = 5.0
    prob['distance_hub2mb'] = 1.912  # length from hub center to main bearing, leave zero if unknown
    prob['gearbox_input_xcm'] = 0.1
    prob['hss_input_length'] = 1.5

    # try this:
    prob['blade_mass'] = 17740.0
    prob['blade_root_diameter'] = 2.5
    prob['blade_length'] = 60.0
    
    # Tower inputs
    prob['tower_top_diameter'] = 3.78  # m

    prob.run_driver()
    prob.model.list_inputs(units=True)#values = False, hierarchical=False)
    prob.model.list_outputs(units=True)#values = False, hierarchical=False)    

    return prob

'''
#Need to update for new structure of drivetrain
def nacelle_example_1p5MW_3pt():

    # test of module for turbine data set

    # 1.5 MW Rotor Variables
    print('----- NREL 1p5MW  Drivetrain - 3 Point Suspension-----')
    nace=Group()
    Drive3pt(nace)
    prob=Problem(nace)
    prob.setup()
    nace.rotor_diameter=77  # m
    nace.rotor_rpm=16.18  # rpm
    nace.drivetrain_efficiency=0.95
    nace.machine_rating=1500
    nace.rotor_torque=1.5 * (nace.machine_rating * 1000 / nace.drivetrain_efficiency) / \
                             (nace.rotor_rpm * (pi / 30)
                              )  # 6.35e6 #4365248.74 # Nm
    nace.rotor_thrust=2.6204e5
    nace.rotor_mass=0.0
    nace.rotor_bending_moment=2.7795e6
    nace.rotor_bending_moment_x=8.4389e5
    nace.rotor_bending_moment_y=-2.6758e6
    nace.rotor_bending_moment_z=7.5222e2
    nace.rotor_thrust=2.6204e5
    nace.rotor_force_y=2.8026e4
    nace.rotor_force_z=-3.4763e5


    # 1p5MW  Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine
    nace.drivetrain_design='geared'
    nace.machine_rating=1500.0  # kW
    nace.gear_ratio=78
    nace.gear_configuration='epp'  # epicyclic-parallel-parallel
    nace.crane=False  # onboard crane not present
    nace.shaft_angle=5.0  # deg
    nace.shaft_ratio=0.10
    nace.Np=[3, 1, 1]
    nace.shaft_type='normal'
    nace.uptower_transformer=False  # True
    nace.shrink_disc_mass=333.3 * nace.machine_rating / 1000.0  # estimated
    nace.carrier_mass=2000.0  # estimated
    nace.mb1Type='SRB'
    nace.mb2Type='SRB'
    nace.flange_length=0.285  # m
    nace.overhang=3.3
    nace.distance_hub2mb=1.535  # length from hub center to main bearing, leave zero if unknown

    # 0 if no fatigue check, 1 if parameterized fatigue check, 2 if known
    # loads inputs
    nace.check_fatigue=0

    # variables if check_fatigue = 1:
    nace.blade_number=3
    nace.cut_in=3.5  # cut-in m/s
    nace.cut_out=20.  # cut-out m/s
    nace.Vrated=11.5  # rated windspeed m/s
    nace.weibull_k=2.2  # windepeed distribution shape parameter
    nace.weibull_A=9.  # windspeed distribution scale parameter
    nace.T_life=20.  # design life in years
    nace.IEC_Class_Letter='B'

    # variables if check_fatigue =2:
    # nace.rotor_thrust_distribution =
    # nace.rotor_thrust_count =
    # nace.rotor_Fy_distribution =
    # nace.rotor_Fy_count =
    # nace.rotor_Fz_distribution =
    # nace.rotor_Fz_count =
    # nace.rotor_torque_distribution =
    # nace.rotor_torque_count =
    # nace.rotor_My_distribution =
    # nace.rotor_My_count =
    # nace.rotor_Mz_distribution =
    # nace.rotor_Mz_count =

    # 1p5MW Tower Variables
    nace.tower_top_diameter=2.3  # m

    prob.run_driver()

    sys_print(nace)

def nacelle_example_1p5MW_4pt():

    # test of module for turbine data set

    print('----- NREL 1p5MW  Drivetrain - 4 Point Suspension-----')
    nace=Group()
    Drive4pt(nace)
    prob=Problem(nace)
    prob.setup()
    nace.rotor_diameter=77  # m
    nace.rotor_rpm=16.18  # rpm
    nace.drivetrain_efficiency=0.95
    nace.machine_rating=1500
    nace.rotor_torque=1.5 * (nace.machine_rating * 1000 / nace.drivetrain_efficiency) / \
                             (nace.rotor_rpm * (pi / 30)
                              )  # 6.35e6 #4365248.74 # Nm
    nace.rotor_thrust=2.6204e5
    nace.rotor_mass=0.0
    nace.rotor_bending_moment=2.7795e6
    nace.rotor_bending_moment_x=8.4389e5
    nace.rotor_bending_moment_y=-2.6758e6
    nace.rotor_bending_moment_z=7.5222e2
    nace.rotor_thrust=2.6204e5
    nace.rotor_force_y=2.8026e4
    nace.rotor_force_z=-3.4763e5

    # 1p5MW  Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine
    nace.drivetrain_design='geared'
    nace.machine_rating=1500.0  # kW
    nace.gear_ratio=78
    nace.gear_configuration='epp'  # epicyclic-parallel-parallel
    nace.crane=False  # True # onboard crane present
    nace.shaft_angle=5.0  # deg
    nace.shaft_ratio=0.10
    nace.Np=[3, 1, 1]
    nace.shaft_type='normal'
    nace.uptower_transformer=False  # True
    nace.shrink_disc_mass=333.3 * nace.machine_rating / 1000.0  # estimated
    nace.carrier_mass=2000.0  # estimated
    nace.mb1Type='CARB'
    nace.mb2Type='SRB'
    nace.flange_length=0.285  # m
    nace.overhang=4
    nace.distance_hub2mb=1.3  # length from hub center to main bearing, leave zero if unknown
    nace.gearbox_cm=0.0

    # 0 if no fatigue check, 1 if parameterized fatigue check, 2 if known
    # loads inputs
    nace.check_fatigue=0

    # variables if check_fatigue = 1:
    nace.blade_number=3
    nace.cut_in=3.5  # cut-in m/s
    nace.cut_out=20.  # cut-out m/s
    nace.Vrated=11.5  # rated windspeed m/s
    nace.weibull_k=2.2  # windepeed distribution shape parameter
    nace.weibull_A=9.  # windspeed distribution scale parameter
    nace.T_life=20.  # design life in years
    nace.IEC_Class_Letter='B'

    # variables if check_fatigue =2:
    # nace.rotor_thrust_distribution =
    # nace.rotor_thrust_count =
    # nace.rotor_Fy_distribution =
    # nace.rotor_Fy_count =
    # nace.rotor_Fz_distribution =
    # nace.rotor_Fz_count =
    # nace.rotor_torque_distribution =
    # nace.rotor_torque_count =
    # nace.rotor_My_distribution =
    # nace.rotor_My_count =
    # nace.rotor_Mz_distribution =
    # nace.rotor_Mz_count =

    # 1p5MW Tower Variables
    nace.tower_top_diameter=2.3  # m

    prob.run_driver()

    # cm_print(nace)
    sys_print(nace)

def nacelle_example_p75_3pt():

    # test of module for turbine data set
    print('----- NREL 750kW Design - 3 Point Suspension----')
    # 0.75MW Rotor Variables
    nace=Group()
    Drive3pt(nace)
    prob=Problem(nace)
    prob.setup()
    nace.rotor_diameter=48.2  # m
    nace.rotor_rpm=22.0  # rpm m/s
    nace.drivetrain_efficiency=0.95
    nace.machine_rating=750
    nace.rotor_torque=1.5 * (nace.machine_rating * 1000 / nace.drivetrain_efficiency) / \
                             (nace.rotor_rpm * (pi / 30)
                              )  # 6.35e6 #4365248.74 # Nm

    nace.rotor_thrust=143000.0  # N
    nace.rotor_mass=0.0  # kg
    nace.rotor_bending_moment=495.6e3
    nace.rotor_bending_moment_x=401.0e3
    nace.rotor_bending_moment_y=495.6e3
    nace.rotor_bending_moment_z=-443.0e3
    nace.rotor_thrust=143000.0
    nace.rotor_force_y=-12600.0
    nace.rotor_force_z=-142.0e3

    # NREL 750 kW Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine
    nace.drivetrain_design='geared'
    nace.machine_rating=750  # kW
    nace.gear_ratio=81.491
    nace.gear_configuration='epp'  # epicyclic-parallel-parallel
    nace.crane=False  # True if onboard crane present
    nace.shaft_angle=5.0  # deg
    nace.shaft_length=2.1  # m
    nace.shaft_ratio=0.10
    nace.Np=[3, 1, 1]
    nace.shaft_type='normal'
    nace.uptower_transformer=False
    nace.shrink_disc_mass=333.3 * nace.machine_rating / 1000.0  # estimated
    nace.carrier_mass=250.  # estimated
    nace.mb1Type='SRB'
    nace.mb2Type='TRB2'
    nace.flange_length=0.285  # m
    nace.overhang=2.26
    nace.distance_hub2mb=1.22  # length from hub center to main bearing, leave zero if unknown
    nace.gearbox_cm=0.8
    nace.blade_root_diameter=1.6

    # 0 if no fatigue check, 1 if parameterized fatigue check, 2 if known
    # loads inputs
    nace.check_fatigue=0

    # variables if check_fatigue = 1:
    nace.blade_number=3
    nace.cut_in=3.  # cut-in m/s
    nace.cut_out=25.  # cut-out m/s
    nace.Vrated=16.  # rated windspeed m/s
    nace.weibull_k=2.2  # windepeed distribution shape parameter
    nace.weibull_A=9.  # windspeed distribution scale parameter
    nace.T_life=20.  # design life in years
    nace.IEC_Class_Letter='A'


    # variables if check_fatigue =2:
    # nace.rotor_thrust_distribution =
    # nace.rotor_thrust_count =
    # nace.rotor_Fy_distribution =
    # nace.rotor_Fy_count =
    # nace.rotor_Fz_distribution =
    # nace.rotor_Fz_count =
    # nace.rotor_torque_distribution =
    # nace.rotor_torque_count =
    # nace.rotor_My_distribution =
    # nace.rotor_My_count =
    # nace.rotor_Mz_distribution =
    # nace.rotor_Mz_count =

    # 0.75MW Tower Variables
    nace.tower_top_diameter=2.21  # m

    prob.run_driver()
    # cm_print(nace)
    sys_print(nace)

def nacelle_example_p75_4pt():

    # test of module for turbine data set
    print('----- NREL 750kW Design - 4 Point Suspension----')
    # 0.75MW Rotor Variables
    nace=Group()
    Drive4pt(nace)
    prob=Problem(nace)
    prob.setup()
    nace.rotor_diameter=48.2  # m
    nace.rotor_rpm=22.0  # rpm
    nace.drivetrain_efficiency=0.95
    nace.machine_rating=750
    nace.rotor_torque=1.5 * (nace.machine_rating * 1000 / nace.drivetrain_efficiency) / \
                             (nace.rotor_rpm * (pi / 30)
                              )  # 6.35e6 #4365248.74 # Nm
    #nace.rotor_torque = 6.37e6 #
    nace.rotor_thrust=143000.0
    nace.rotor_mass=0.0
    nace.rotor_bending_moment=459.6e3
    nace.rotor_bending_moment_x=401.0e3
    nace.rotor_bending_moment_y=459.6e3
    nace.rotor_bending_moment_z=-443.0e3
    nace.rotor_thrust=143000.0
    nace.rotor_force_y=-12600.0
    nace.rotor_force_z=-142.0e3

    # NREL 750 kW Drivetrain variables
    # geared 3-stage Gearbox with induction generator machine
    nace.drivetrain_design='geared'
    nace.machine_rating=750  # kW
    nace.gear_ratio=81.491  # as listed in the 5 MW reference document
    nace.gear_configuration='epp'  # epicyclic-parallel-parallel
    nace.crane=False  # True # onboard crane present
    nace.shaft_angle=5.0  # deg
    nace.shaft_length=2.1  # m
    nace.shaft_ratio=0.10
    nace.Np=[3, 1, 1]
    nace.shaft_type='normal'
    nace.uptower_transformer=False  # True
    nace.shrink_disc_mass=333.3 * nace.machine_rating / 1000.0  # estimated
    nace.carrier_mass=1000.0  # estimated
    nace.mb1Type='SRB'
    nace.mb2Type='TRB2'
    nace.flange_length=0.338  # m
    nace.overhang=2.26
    nace.distance_hub2mb=1.22  # 0.007835*rotor_diameter+0.9642 length from hub center to main bearing, leave zero if unknown
    nace.gearbox_cm=0.90

    # 0 if no fatigue check, 1 if parameterized fatigue check, 2 if known
    # loads inputs
    nace.check_fatigue=0

    # variables if check_fatigue = 1:
    nace.blade_number=3
    nace.cut_in=3.  # cut-in m/s
    nace.cut_out=25.  # cut-out m/s
    nace.Vrated=16.  # rated windspeed m/s
    nace.weibull_k=2.2  # windepeed distribution shape parameter
    nace.weibull_A=9.  # windspeed distribution scale parameter
    nace.T_life=20.  # design life in years
    nace.IEC_Class_Letter='A'

    # variables if check_fatigue =2:
    # nace.rotor_thrust_distribution =
    # nace.rotor_thrust_count =
    # nace.rotor_Fy_distribution =
    # nace.rotor_Fy_count =
    # nace.rotor_Fz_distribution =
    # nace.rotor_Fz_count =
    # nace.rotor_torque_distribution =
    # nace.rotor_torque_count =
    # nace.rotor_My_distribution =
    # nace.rotor_My_count =
    # nace.rotor_Mz_distribution =
    # nace.rotor_Mz_count =

    # 0.75MW Tower Variables
    nace.tower_top_diameter=2.21  # m

    prob.run_driver()

    sys_print(nace)
'''

if __name__ == '__main__':
    ''' Main runs through tests of several drivetrain configurations with known component masses and dimensions '''

    debug = True
    #debug = False
    
    nacelle_example_5MW_baseline_3pt(debug=debug)

    #nacelle_example_5MW_baseline_4pt(debug=debug)
    
    '''
    nacelle_example_1p5MW_3pt()

    nacelle_example_1p5MW_4pt()

    nacelle_example_p75_3pt()

    nacelle_example_p75_4pt()'''