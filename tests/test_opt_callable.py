# -*- coding: utf-8 -*-
import unittest
import numpy as N

from tracer import optics_callables
from tracer.ray_bundle import RayBundle
from tracer.flat_surface import FlatGeometryManager

class TestReflective(unittest.TestCase):
    def setUp(self):
        """Set up the ray bundle and geometry"""
        dir = N.c_[[1, 1, -1], [-1, 1, -1], [-1, -1, -1], [1, -1, -1]] / N.sqrt(3)
        position = N.c_[[0,0,1], [1,-1,1], [1,1,1], [-1,1,1]]
        en = N.r_[100, 200, 300, 400]
        self._bund = RayBundle(position, dir, energy=en)
        
        self.gm = FlatGeometryManager()
        self.prm = self.gm.find_intersections(N.eye(4), self._bund)
    
    def test_with_absorptivity(self):
        """A correct bundle is generated by reflective, with energy reduced correctly"""
        reflective = optics_callables.Reflective(0.1)
        self.gm.select_rays(N.arange(4))
        outg = reflective(self.gm, self._bund, N.arange(4))
        
        correct_pts = N.zeros((3,4))
        correct_pts[:2,0] = 1
        N.testing.assert_array_equal(outg.get_vertices(), correct_pts)
        
        correct_dirs = N.c_[[1, 1, 1], [-1, 1, 1], [-1, -1, 1], [1, -1, 1]] / N.sqrt(3)
        N.testing.assert_array_equal(outg.get_directions(), correct_dirs)
        
        N.testing.assert_array_equal(outg.get_energy(), N.r_[90, 180, 270, 360])
        N.testing.assert_array_equal(outg.get_parents(), N.arange(4))
    
    def test_without_absorptivity(self):
        """Perfect mirroring works"""
        reflective = optics_callables.Reflective(0)
        self.gm.select_rays(N.arange(4))
        outg = reflective(self.gm, self._bund, N.arange(4))
        N.testing.assert_array_equal(outg.get_energy(), N.r_[100, 200, 300, 400])
    
    def test_receiver(self):
        """A receiver memorizes all lifetime hits"""
        receiver = optics_callables.ReflectiveReceiver() # Perfect absorber
        self.gm.select_rays(N.arange(4))
        
        # Round one:
        outg = receiver(self.gm, self._bund, N.arange(4))
        N.testing.assert_array_equal(outg.get_energy(), 0)
        absorbed, hits = receiver.get_all_hits()
        N.testing.assert_array_equal(absorbed, N.r_[100, 200, 300, 400])
        correct_pts = N.zeros((3,4))
        correct_pts[:2,0] = 1
        N.testing.assert_array_equal(hits, correct_pts)
        
        # Round two:
        outg = receiver(self.gm, self._bund, N.arange(4))
        absorbed, hits = receiver.get_all_hits()
        N.testing.assert_array_equal(absorbed, N.tile(N.r_[100, 200, 300, 400], 2))
        N.testing.assert_array_equal(hits, N.tile(correct_pts, (1,2)))

class TestRefractiveHomogenous(unittest.TestCase):
    def test_all_refracted(self):
        dir = N.c_[[1, 1, -1], [-1, 1, -1], [-1, -1, -1], [1, -1, -1]] / N.sqrt(3)
        position = N.c_[[0,0,1], [1,-1,1], [1,1,1], [-1,1,1]]
        en = N.r_[100, 200, 300, 400]
        bund = RayBundle(position, dir, energy=en, ref_index=N.ones(4))
        
        gm = FlatGeometryManager()
        prm = gm.find_intersections(N.eye(4), bund)
        refractive = optics_callables.RefractiveHomogenous(1,1.5)
        selector = N.array([0, 1, 3])
        gm.select_rays(selector)
        outg = refractive(gm, bund, selector)
        
        correct_pts = N.zeros((3,4))
        correct_pts[:2,0] = 1
        correct_pts = N.hstack((correct_pts[:,selector], correct_pts[:,selector]))
        N.testing.assert_array_equal(outg.get_vertices(), correct_pts)
        
        norm = N.c_[gm.get_normals()[:,0]]
        correct_refl_cos = -(dir*norm).sum(axis=0)[selector]
        correct_refr_cos = -N.sqrt(1 - (1./1.5)**2*(1 - correct_refl_cos**2))
        outg_cos = (outg.get_directions()*norm).sum(axis=0)
        N.testing.assert_array_equal(outg_cos, N.r_[correct_refl_cos, correct_refr_cos])
        
        N.testing.assert_array_equal(outg.get_energy().reshape(2,-1).sum(axis=0), \
            N.r_[100, 200, 400]) # reflection and refraction sum to 100%
        N.testing.assert_array_equal(outg.get_parents(), N.tile(selector, 2))
    
    def test_TIR(self):
        dir = N.c_[[0, N.cos(N.pi/180), -N.sin(N.pi/180)]]
        position = N.c_[[0,0,1]]
        en = N.r_[100]
        bund = RayBundle(position, dir, energy=en, ref_index=N.r_[1.5])
        
        gm = FlatGeometryManager()
        prm = gm.find_intersections(N.eye(4), bund)
        refractive = optics_callables.RefractiveHomogenous(1.,1.5)
        selector = N.r_[0]
        gm.select_rays(selector)
        outg = refractive(gm, bund, selector)
        
        self.failUnlessEqual(outg.get_vertices().shape, (3,1))
        N.testing.assert_array_equal(outg.get_directions(), 
            N.c_[[0, N.cos(N.pi/180), N.sin(N.pi/180)]])
        N.testing.assert_array_equal(outg.get_energy(), N.r_[100])
        N.testing.assert_array_equal(outg.get_parents(), N.r_[0])

class TestAbsorberReflector(unittest.TestCase):
    def test_up_down(self):
        """Rays coming from below are absorbed, from above reflected"""
        going_down = N.c_[[1, 1, -1], [-1, 1, -1], [-1, -1, -1], [1, -1, -1]] / N.sqrt(3)
        going_up = going_down.copy()
        going_up[2] = 1 / N.sqrt(3)
        
        pos_up = N.c_[[0,0,1], [1,-1,1], [1,1,1], [-1,1,1]]
        pos_down = pos_up.copy()
        pos_down[2] = -1

        bund = RayBundle()
        bund.set_directions(N.hstack((going_down, going_up)))
        bund.set_vertices(N.hstack((pos_up, pos_down)))
        bund.set_energy(N.tile(100, 8))
        bund.set_ref_index(N.tile(1, 8))
        
        gm = FlatGeometryManager()
        prm = gm.find_intersections(N.eye(4), bund)
        absref = optics_callables.AbsorberReflector(0.)
        selector = N.arange(8)
        gm.select_rays(selector)
        outg = absref(gm, bund, selector)
        
        e = outg.get_energy()
        N.testing.assert_array_equal(e[:4], 100)
        N.testing.assert_array_equal(e[4:], 0)

